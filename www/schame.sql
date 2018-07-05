drop database if exists awesome;
create database awesome;

use awesome;

grant select, insert, delete on awesome.* to 'pawn'@'localhost' identified by 'pawn';

create table users (
    `id` varchar (50) not null,
    `email` varchar(50) not null,
    `password` varchar(50) not null,
    `admin` varchar(50) not null,
    `name` varchar(50) not null,
    `image` varchar(500) not null,
    `create_time` real not null,
    unique key  `idx_email` (`email`),
    key `idx_create_time` (`create_time`),
    primary key (`id`)
) engine=innodb default charset=utf8;

create table blog (
  `id` varchar(50) not null,
  `user_id` varchar(50) not null,
  `user_name` varchar(50) not null,
  `user_image` varchar(500) not null,
  `name` varchar(50) not null,
  `summary` varchar(200) not null,
  `content` mediumtext not null,
  `create_time` real not null,
  key `idx_create_time` (`create_time`),
  primary key (`id`)
) engine=innodb default charset=utf8;

create table comments (
  `id` varchar(50) not null,
  `blog_id` varchar(50) not null,
  `user_id` varchar(50) not null,
  `user_name` varchar(50) not null,
  `user_image` varchar(500) not null,
  `content` mediumtext not null,
  `create_time` real not null,
  key `idx_create_time` (`create_time`),
  primary key (`id`)
) engine=innodb default charset=utf8;
